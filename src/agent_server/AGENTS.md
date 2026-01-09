# AGENTS.md - `src/agent_server/` (Server Domain Router)

This document is upstream context for the entire `src/agent_server/` tree.
Layer-specific implementation details live in downstream `AGENTS.md` files.

## Purpose
- Provide server-wide rules, boundaries, and shared invariants for the FastAPI Agent Protocol server.
- Route work to the correct layer document first.

## Non-Goals
- Do not restate a full catalog of endpoints/services/DB schema here.
- Do not duplicate file-level implementation details; keep those downstream.

---

## Scope & Boundaries

### In scope (this directory owns)
- Agent Protocol–compatible FastAPI app (`src/agent_server/main.py`)
- Request handling structure: `api/` → `services/` → `core/` → DB
- Cross-cutting rules for auth, multi-tenancy, observability, and middleware

### Out of scope (read downstream)
- Graph implementations (nodes/tools/interrupt): `graphs/AGENTS.md`
- Migration operations/timelines: `alembic/AGENTS.md`
- Test rules/pyramid/fixtures: `tests/AGENTS.md`

---

## MUST-KNOW (Invariants)
- [MUST] LangGraph is the single source of truth for execution and state: conversational state is stored via LangGraph checkpointer/store; ORM remains metadata-centric.
- [MUST] Preserve layer boundaries:
  - `api/`: HTTP contract (validation/response shapes/Depends)
  - `services/`: business logic and orchestration
  - `core/`: infrastructure (DB/auth/RLS/serialization/SSE/etc.)
- [MUST] `src/agent_server/main.py` must add `graphs/` to `sys.path` before importing server modules; breaking this order can break dynamic graph imports.
- [MUST] Middleware request order is: Audit → RateLimit → Authentication → DoubleEncodedJSON → CORS → Router.
  - Source of truth: middleware registration order in `src/agent_server/main.py` (`add_middleware(...)`).
- [MUST] Behavior changes significantly by auth mode:
  - With `AUTH_TYPE=noop`, `auth.py` returns `is_authenticated=False`, so endpoints using `get_current_user()` may return 401.
  - For authenticated calls in dev, use `AUTH_TYPE=custom` + `Authorization: Bearer dev-token` (example implementation), or adjust `auth.py`.
- [MUST] Multi-tenancy scope is `identity` (user_id) + optional `org_id`; missing filters can leak data.
- [MUST] If Postgres RLS is enabled, failure to set RLS context is security-critical and must abort the request (`src/agent_server/core/rls.py`).
- [SHOULD] Optional infra follows a "disabled when missing" pattern (cache/rate limit/OTEL). Production fail-open/closed must be explicit via env vars.

---

## Startup / Shutdown (Lifespan) Checkpoints

`src/agent_server/main.py` `lifespan()` depends on this initialization order (summary):
- OpenTelemetry setup
- DB initialization (`db_manager.initialize()`)
- Optional: Redis cache / rate limiter initialization
- LangGraphService initialization (graph loading + default assistant creation)
- Custom endpoint route registration
- Start background tasks (event store cleanup/TTL, cron, audit outbox mover, partition bootstrap, etc.)

The code is the source of truth; if this document drifts, update the document.

---

## Common Tasks (Router)

### 1) Add a new endpoint
1. Define request/response models in `src/agent_server/models/`
2. Add business logic in `src/agent_server/services/` (prefer a service method)
3. Implement the router in `src/agent_server/api/` + Depends (auth/session/rate limiting)
4. If needed, update `src/agent_server/core/orm.py` + create an Alembic migration
5. Add tests in `tests/` at the right level (unit/integration/e2e)

### 2) Debug multi-tenancy / permission issues
- Entry points: `src/agent_server/core/auth_middleware.py`, `src/agent_server/core/auth_deps.py`
- RLS: `src/agent_server/core/rls.py`, `src/agent_server/core/orm.py#get_session_with_rls`
- API-layer filtering: check each router’s `*_access_filter` helpers

### 3) Debug streaming (SSE) issues
- Core: `src/agent_server/services/streaming_service.py`, `src/agent_server/services/event_store.py`, `src/agent_server/services/broker.py`
- HTTP contract: `src/agent_server/api/runs.py` (includes `Last-Event-ID`)

### 4) Add/modify a graph
- Update `open_langgraph.json` + implement the graph package + ensure the `graph` export
- Detailed guide: `graphs/AGENTS.md`

---

## References (Downstream)
- Core: `src/agent_server/core/AGENTS.md`
- Services: `src/agent_server/services/AGENTS.md`
- API: `src/agent_server/api/AGENTS.md`
- Models: `src/agent_server/models/AGENTS.md`
- Middleware: `src/agent_server/middleware/AGENTS.md`
- Observability: `src/agent_server/observability/AGENTS.md`
- A2A: `src/agent_server/a2a/AGENTS.md`
- Utils: `src/agent_server/utils/AGENTS.md`

## Keywords Router
- `auth`, `AUTH_TYPE`, `get_current_user` → `src/agent_server/core/auth_*.py`, `auth.py`
- `tenant`, `org_id`, `RLS` → `src/agent_server/core/rls.py`, `src/agent_server/core/orm.py`
- `SSE`, `Last-Event-ID`, `stream` → `src/agent_server/services/streaming_service.py`, `src/agent_server/api/runs.py`
- `LangGraphService`, `open_langgraph.json` → `src/agent_server/services/langgraph_service.py`, `open_langgraph.json`
