# (Reference) Core Layer (`src/agent_server/core/`)

> This is a long-form reference companion to `src/agent_server/core/AGENTS.md`.
> Prefer the MUST-KNOW guide in `src/agent_server/core/AGENTS.md`.

## What this layer does

The Core layer owns infrastructure and shared primitives used across the server:

- database engine/session lifecycle (async SQLAlchemy)
- ORM models for metadata tables (assistants/threads/runs/etc.)
- optional Postgres RLS enforcement and request-scoped RLS context
- authentication context propagation (middleware + dependencies)
- LangGraph persistence adapters (checkpointer/store wiring)
- SSE formatting (headers + event serialization)
- rate limiting primitives (enforcers/limiters) and resilience helpers

API and Services should treat Core as the “single source of truth” for these concerns.

## Invariants (high-signal)

- LangGraph is the single source of truth for **graph execution and state persistence**.
  - ORM tables are primarily for **metadata**.
- Tenant scoping is security-critical.
  - Always apply `identity` and (when applicable) `org_id`.
  - If using RLS, failure to set the RLS context must fail the request.
- External input is untrusted.
  - Be careful with headers, URLs, and user-provided identifiers.

## Key modules (examples)

- `database.py`: engine/session init and teardown
- `orm.py`: SQLAlchemy models + session factories + helpers
- `rls.py`: Postgres RLS context management (request scoped)
- `auth_ctx.py`, `auth_middleware.py`, `auth_deps.py`: auth context + `get_current_user`
- `sse.py`: SSE headers + message formatting helpers
- `checkpointer/`: LangGraph checkpointer/store adapters
- `serializers/`: JSON serialization helpers for LangGraph objects
- `rate_limiter.py`, `rate_limit_enforcer.py`: rate limiting primitives
- `resilience.py`: bounded timeouts / best-effort wrappers

## Common tasks

### Add a new metadata table

1. Define the ORM model in `src/agent_server/core/orm.py`.
2. Create an Alembic migration.
3. Ensure tenant scoping is enforced in queries (and/or RLS policies).

### Change auth/tenancy behavior

1. Review `auth.py` (auth type) and `auth_*` modules in Core.
2. Confirm middleware ordering in `src/agent_server/main.py`.
3. Add tests that prove isolation.

### Adjust SSE behavior

1. Update formatting helpers in `src/agent_server/core/sse.py`.
2. Update orchestration in `src/agent_server/services/streaming_service.py`.
3. Validate reconnect/replay via `Last-Event-ID`.

## Common pitfalls

- Mixing sync/async DB sessions or leaking sessions across requests.
- Implementing ad-hoc SSE formatting in services/API (should centralize in Core).
- Forgetting tenant filters when selecting by “public” IDs.
- Over-storing conversation/state data in ORM instead of using LangGraph persistence.

## References

- `src/agent_server/core/AGENTS.md`
- `src/agent_server/AGENTS.md`
- `alembic/AGENTS.md`

