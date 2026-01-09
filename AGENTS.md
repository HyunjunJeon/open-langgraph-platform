# AGENTS.md (Root) — Open LangGraph Platform

This file contains upstream (always-on) agent guidance for the entire repository.
Rule of thumb: keep only MUST-KNOW here; delegate everything else to module-level `AGENTS.md` (downstream).

## Project Charter
- Goal: A FastAPI-based Agent Protocol server that can run LangGraph Platform features on self-hosted infrastructure.
- Philosophy: LangGraph is the single source of truth for state and graph execution; FastAPI is only an Agent Protocol–compatible HTTP layer.
- Operations: PostgreSQL (production) + SSE streaming + auth/multi-tenancy + optional observability/cache/rate limiting.

## Hard Rules (MUST)
- [MUST] Use LangGraph packages and concepts directly; do not add unnecessary wrappers/abstractions.
- [MUST] Do not break Agent Protocol compatibility; keep contracts used by official SDKs/clients.
- [MUST] Treat "state" as LangGraph responsibility (checkpointer/store); keep ORM focused on metadata.
- [MUST] Always apply multi-tenancy scope (`identity`, `org_id`); missing filters can leak data (review filtering/RLS).
- [MUST] Never trust external input (SSRF/XSS/header injection/secrets leakage).

## Source of Truth (Always Check Here)
- Python/deps: `pyproject.toml` (`requires-python = ">=3.13"`)
- Graph registry: `open_langgraph.json`
- Env template: `.env.example`
- Local runtime (Docker): `docker-compose.yml`
- Server entrypoint: `src/agent_server/main.py`
- AGENTS hierarchy design: `agents_hierarchy_design.md`
- (Reference) Legacy structure guide: `docs/structure-guide.md`

---

## Where To Read Next (AGENTS Router)

### Server Domain
- `src/agent_server/AGENTS.md` (server-wide rules/boundaries)
  - Core: `src/agent_server/core/AGENTS.md`
    - Checkpointer/Store adapters: `src/agent_server/core/checkpointer/AGENTS.md`
    - Serialization: `src/agent_server/core/serializers/AGENTS.md`
  - Services: `src/agent_server/services/AGENTS.md`
    - Agent Auth (agent identity/credentials): `src/agent_server/services/agent_auth/AGENTS.md`
    - Federation (remote agents/peers): `src/agent_server/services/federation/AGENTS.md`
  - API: `src/agent_server/api/AGENTS.md`
  - Models: `src/agent_server/models/AGENTS.md`
  - Middleware: `src/agent_server/middleware/AGENTS.md`
  - Observability: `src/agent_server/observability/AGENTS.md`
  - A2A: `src/agent_server/a2a/AGENTS.md`
  - Utils: `src/agent_server/utils/AGENTS.md`

### Graph Domain
- `graphs/AGENTS.md` (graph rules/registration/patterns)
  - `graphs/react_agent/AGENTS.md`
  - `graphs/react_agent_hitl/AGENTS.md`
  - `graphs/subgraph_agent/AGENTS.md`

### DB / Tests / Docs / Deploy
- DB migrations: `alembic/AGENTS.md`
- Tests: `tests/AGENTS.md`
- Docs: `docs/AGENTS.md`
- Deploy: `deployments/AGENTS.md`, `deployments/docker/AGENTS.md`

---

## Quick Commands (Minimal)
- Dependencies: `uv sync --all-extras`
- Tests: `uv run pytest`
- Format/lint/type-check: `make format`, `make lint`, `make type-check`
- Local server (Docker): `docker compose up open-langgraph`
- Local server (direct): `uv run python run_server.py`

---

## Additional MUST-KNOW

### Naming Conventions
- The project was renamed from "Aegra" to "Open LangGraph" (Oct 2025); avoid introducing the old name in new code/docs.
- Use `open-langgraph` for Docker/service naming, `open_langgraph` for Python/DB/config, and "Open LangGraph" for display strings.

### Graph Registry Config Resolution
- The graph registry config path is resolved in this order: `OPEN_LANGGRAPH_CONFIG` → configured `config_path` (if it exists) → `./open_langgraph.json` → `./langgraph.json` (legacy fallback).

### Validation (Before Finishing)
- [SHOULD] Run `uv run pytest` and relevant checks (`make lint`, `make type-check`) for changes you make.

---

## Task Router (Keyword → First Files to Open)
- `auth`, `AUTH_TYPE`, `permissions` → `src/agent_server/core/auth_*.py`, `auth.py`, `src/agent_server/AGENTS.md`
- `tenant`, `org_id`, `RLS` → `src/agent_server/core/rls.py`, `src/agent_server/core/orm.py`, `src/agent_server/AGENTS.md`
- `SSE`, `stream`, `Last-Event-ID`, `replay` → `src/agent_server/services/streaming_service.py`, `src/agent_server/services/event_store.py`, `src/agent_server/api/runs.py`
- `store`, `memory` → `src/agent_server/api/store.py`, `src/agent_server/core/database.py`
- `federation`, `remote`, `SSRF` → `src/agent_server/services/federation/AGENTS.md`, `src/agent_server/utils/url_validator.py`
- `A2A` → `src/agent_server/a2a/AGENTS.md`
- `new graph`, `interrupt` → `graphs/AGENTS.md`, `open_langgraph.json`
