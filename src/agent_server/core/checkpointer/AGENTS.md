# AGENTS.md - `src/agent_server/core/checkpointer/` (LangGraph Persistence Adapters)

This directory is an adapter layer that standardizes LangGraph checkpointer/store backend selection.

## Purpose
- Create checkpointer/store instances consistently from env vars, DSNs, and options.
- Support Postgres/SQLite/Memory backends behind a uniform interface.
- Provide redaction so secrets do not leak through logs/health checks.

## Non-Goals
- Do not define ORM (metadata) models or FastAPI dependencies.
- Do not own graph execution logic (delegated to the Services layer).

---

## MUST-KNOW (Invariants)
- [MUST] Backend selection is owned by `AdapterFactory.create_adapter()`.
  - With `CHECKPOINTER_BACKEND=auto`, selection depends on whether `DATABASE_URL` is SQLite.
  - File: `src/agent_server/core/checkpointer/factory.py`
- [MUST] Postgres DSNs must be normalized to `postgresql://` (required by LangGraph Postgres saver/store).
  - `postgresql+asyncpg://` and `postgres://` are converted.
  - File: `src/agent_server/core/checkpointer/postgres.py`
- [MUST] Never log raw DSNs/options.
  - `CheckpointerAdapter.info()` must return redacted DSN/options.
  - File: `src/agent_server/core/checkpointer/base.py`
- [MUST] The SQLite backend is optional.
  - If not installed, it must raise an explicit error; install `langgraph-checkpoint-sqlite` if needed.
  - File: `src/agent_server/core/checkpointer/sqlite.py`
- [SHOULD] The `setup_on_init` policy may differ per backend.
  - Postgres default: `True` (runs setup)
  - SQLite default: `False` (reduces cost for local/tests)

---

## Config Surface (Environment Variables)

Actual parsing/application happens in `src/agent_server/core/database.py`.

- `CHECKPOINTER_BACKEND`: `auto|postgres|sqlite|memory`
- `CHECKPOINTER_DSN`: backend connection string override
- `CHECKPOINTER_OPTIONS`: JSON object string, fanned out into backend-specific options
  - Example: `{"setup_on_init": true, "checkpointer": {...}, "store": {...}}`

---

## Extending (Add a New Backend)
1. Implement `CheckpointerAdapter` (DSN/options parsing, lazy init, close)
2. Register it in `AdapterFactory._ensure_default_adapters()` (or use runtime registration API)
3. Ensure `info()` redacts secrets in DSNs/options

---

## References
- DB manager (uses adapters): `src/agent_server/core/database.py`
- LangGraphService (uses checkpointer at compile time): `src/agent_server/services/langgraph_service.py`
