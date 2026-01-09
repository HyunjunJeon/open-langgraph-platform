# AGENTS.md - `src/agent_server/models/` (Pydantic Schemas)

This document keeps only MUST-KNOW guidance for `src/agent_server/models/`.
Long-form details are delegated to: `docs/agents_reference/models-layer.md`.

## Purpose
- Define request/response schemas for Agent Protocol and server extensions (org/RBAC/audit/etc.).
- Keep schemas as the single source of truth for FastAPI validation and serialization.

## Non-Goals
- Business logic is owned by `src/agent_server/services/`.
- DB ORM models/sessions are owned by `src/agent_server/core/orm.py`.

---

## Scope & Boundaries

### In scope (this layer owns)
- Pydantic v2 models (requests/responses, enums, validators)
- Agent Protocol shape compatibility (especially runs/threads/assistants/store)
- Operational/enterprise API schemas (organization/rbac/audit/flags/cron/etc.)

### Boundary rules
- [MUST] Models should be as pure as possible (no network/DB/service calls).
- [SHOULD] Names/fields are part of the API contract; evaluate SDK/backward-compat impact before changes.
- [SHOULD] Prefer ORM → Pydantic via `model_validate(..., from_attributes=True)`.

---

## MUST-KNOW (Invariants)
- [MUST] Pydantic v2 codebase (`BaseModel`, `model_validator`, `ConfigDict`).
- [MUST] For models with alias/serialization policy, explicitly set config such as `populate_by_name=True`.
- [MUST] Agent Protocol error response shape is owned by `errors.py`.
- [SHOULD] Keep consistent separation of LangGraph execution "config vs context" parameters (assistants/runs models).

---

## What’s Here (Map)

Core Agent Protocol:
- `assistants.py`, `threads.py`, `runs.py`, `store.py`, `auth.py`, `errors.py`

Operational/enterprise extensions:
- `organization.py`, `rbac.py`, `audit.py`
- `rate_limit.py`, `rate_limit_rules.py`
- `feature_flags.py`, `crons.py`, `custom_endpoint.py`
- `a2a.py`

---

## Common Tasks

### 1) Add a new API feature
1. Add/update domain models in `src/agent_server/models/<domain>.py`
2. Wire request/response models in routers (`src/agent_server/api/...`)
3. Wire service-layer logic (`src/agent_server/services/...`)
4. If needed, update ORM/migrations

### 2) Preserve compatibility
- Changing Agent Protocol shapes is likely a breaking change → minimize, and consider versioning/release notes.

---

## References
- API layer: `src/agent_server/api/AGENTS.md`
- Services layer: `src/agent_server/services/AGENTS.md`
- Core ORM: `src/agent_server/core/orm.py`
- (Reference) Legacy long-form doc: `docs/agents_reference/models-layer.md`

## Keywords Router
- `RunCreate`, `Run`, `Command`, `interrupt` → `src/agent_server/models/runs.py`
- `ThreadState`, `Checkpoint` → `src/agent_server/models/threads.py`
- `Store*`, `namespace` → `src/agent_server/models/store.py`
- `AgentProtocolError` → `src/agent_server/models/errors.py`
