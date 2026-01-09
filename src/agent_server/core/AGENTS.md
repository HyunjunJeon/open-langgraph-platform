# AGENTS.md - `src/agent_server/core/` (Core Infrastructure)

This document keeps only MUST-KNOW guidance for the `src/agent_server/core/` tree.
Long-form details are delegated to: `docs/agents_reference/core-layer.md`.

## Purpose
- Provide shared infrastructure: DB connections/sessions, LangGraph persistence (checkpointer/store), auth context, RLS, SSE, and serialization.

## Non-Goals
- API endpoint contracts are owned by `src/agent_server/api/AGENTS.md`.
- Business logic/orchestration is owned by `src/agent_server/services/AGENTS.md`.
- Graph implementations are owned by `graphs/AGENTS.md`.

---

## Scope & Boundaries

### In scope (this layer owns)
- DB manager: SQLAlchemy engine (metadata) + LangGraph checkpointer/store (state)
- ORM session creation (request-scoped `AsyncSession`)
- Auth middleware/dependencies (`get_current_user`) and auth context injection for graph nodes
- Postgres RLS context setup (optional)
- SSE formatting and shared serialization utilities
- Resilience and optional infra initialization support (cache/rate limiting)

### Out of scope
- API/Services decide "which resources to read/write under which policy".
- Long-term memory Store API contract is owned by `src/agent_server/api/store.py`.

---

## MUST-KNOW (Invariants)

### DatabaseManager (`db_manager`)
- [MUST] The global `db_manager` is managed in the server lifespan via `initialize()` / `close()`.
  - File: `src/agent_server/core/database.py`, called from: `src/agent_server/main.py`
- [MUST] Separate responsibilities:
  - `get_engine()` → SQLAlchemy metadata tables (assistant/thread/run/…)
  - `get_checkpointer()` / `get_store()` → LangGraph state and long-term store
- [MUST] Support both Postgres and SQLite.
  - If `DATABASE_URL` starts with `sqlite...`, run in SQLite mode.
- [MUST] The checkpointer/store backend is selected via adapters.
  - Details: `src/agent_server/core/checkpointer/AGENTS.md`

### ORM Session / Multi-tenancy / RLS
- [MUST] Standardize on `get_session()` (no RLS) and `get_session_with_rls()` (with RLS).
  - File: `src/agent_server/core/orm.py`
- [MUST] When Postgres RLS is enabled, failure to set RLS context is security-critical and must abort the request.
  - File: `src/agent_server/core/rls.py`
- [REF] This codebase currently relies heavily on application-level filtering (`user_id`/`org_id`).
  - RLS is optional; expanding it requires auditing APIs and services.

### Authentication (LangGraph SDK Auth → Starlette)
- [MUST] `auth_middleware.py` dynamically loads the `auth` instance from the repo-root `auth.py`.
  - Files: `src/agent_server/core/auth_middleware.py`, `auth.py`
- [MUST] `get_current_user()` requires `request.user.is_authenticated == True`.
  - With `AUTH_TYPE=noop`, `is_authenticated=False` by default, so protected endpoints may return 401.
  - Files: `src/agent_server/core/auth_deps.py`, `auth.py`
- [REF] For graph nodes that need user context, use `with_auth_ctx()` / `get_auth_ctx()` from `auth_ctx.py`.

### SSE / Serialization
- [MUST] SSE format/headers are owned by `src/agent_server/core/sse.py`.
- [MUST] Event ID rules are owned by utils: `{run_id}_event_{seq}`.
  - File: `src/agent_server/utils/sse_utils.py`
- [REF] Serialization details: `src/agent_server/core/serializers/AGENTS.md`

---

## Common Tasks

### 1) Add a new metadata table/field
1. Update `src/agent_server/core/orm.py`
2. Create/apply an Alembic migration (see `alembic/AGENTS.md`)
3. Update services/models/tests

### 2) Change the checkpointer/store backend
- Adjust env vars (`CHECKPOINTER_BACKEND`, `CHECKPOINTER_DSN`, `CHECKPOINTER_OPTIONS`).
- Details: `src/agent_server/core/checkpointer/AGENTS.md`, `.env.example`

### 3) Debug authentication
- Middleware loading: `src/agent_server/core/auth_middleware.py`
- FastAPI dependency: `src/agent_server/core/auth_deps.py`
- Configuration: `auth.py`, `.env.example`

---

## References
- Upstream (server-wide rules): `src/agent_server/AGENTS.md`
- Checkpointer/Store: `src/agent_server/core/checkpointer/AGENTS.md`
- Serializers: `src/agent_server/core/serializers/AGENTS.md`
- Alembic: `alembic/AGENTS.md`
- (Reference) Legacy long-form doc: `docs/agents_reference/core-layer.md`

## Keywords Router
- `db_manager`, `DATABASE_URL`, `sqlite`, `postgres` → `src/agent_server/core/database.py`
- `checkpointer`, `store`, `CHECKPOINTER_*` → `src/agent_server/core/checkpointer/AGENTS.md`
- `get_session`, `RLS`, `org_id` → `src/agent_server/core/orm.py`, `src/agent_server/core/rls.py`
- `AUTH_TYPE`, `get_current_user` → `auth.py`, `src/agent_server/core/auth_deps.py`
- `SSE`, `Last-Event-ID`, `serializer` → `src/agent_server/core/sse.py`, `src/agent_server/core/serializers/AGENTS.md`
