# AGENTS.md - `src/agent_server/services/` (Business Logic & Orchestration)

This document keeps only MUST-KNOW guidance for `src/agent_server/services/`.
Long-form details are delegated to: `docs/agents_reference/services-layer.md`.

## Purpose
- Own business logic and orchestration between the API layer and Core infrastructure.
- Provide LangGraph graph load/cache/exec configuration, SSE streaming, event persistence, and server operational features (org/RBAC/quotas/etc.).

## Non-Goals
- HTTP contracts (endpoints/request/response shapes) are owned by `src/agent_server/api/AGENTS.md`.
- DB sessions/RLS/auth/SSE formatting/serialization infrastructure is owned by `src/agent_server/core/AGENTS.md`.

---

## Scope & Boundaries

### In scope (this layer owns)
- LangGraph graph loading/compilation/caching and runtime context injection
- Run streaming (SSE) orchestration: broker ↔ event_store ↔ converter
- Operational features: org/permissions/quotas/rate limiting/audit outbox/cron/background cleanup
- Remote agent discovery/invocation support (A2A/Federation) with security protections

### Boundary rules
- [MUST] Services should not depend directly on FastAPI routers or Request objects (prefer primitives/Pydantic/`AsyncSession`).
- [MUST] DB access must go through Core sessions/engines/managers (do not create engines directly).
- [SHOULD] Consider `TracedService` inheritance or `@traced_service` for observability.

---

## MUST-KNOW (Invariants)

### LangGraphService (`langgraph_service.py`)
- [MUST] The single source of truth for graph registration is `open_langgraph.json`.
- [MUST] Graphs are imported dynamically, compiled, and cached (performance + consistency).
- [MUST] A deterministic UUID "default assistant" may be auto-created per `graph_id` (stable across restarts).
- [MUST] A2A-compatible graphs may be auto-registered in the Agent Registry.

### StreamingService / Broker / EventStore
- [MUST] Streaming uses a dual system: an in-memory broker + a persistent event store.
  - Live consumers: `broker.py`
  - Replay on reconnect: `event_store.py`
- [MUST] Broker backpressure is controlled via env vars (operationally important):
  - `BROKER_QUEUE_MAXSIZE` (default 1000)
  - `BROKER_BACKPRESSURE_POLICY=block|drop_oldest`
- [MUST] With batched event persistence, a very fast terminal run may reach a terminal state before all events flush.
  - Mitigation hook: `StreamingService.flush_run_events(run_id)`
- [REF] Event format conversion: `event_converter.py` (LangGraph raw → stored/transmitted SSE shape)

### Optional / Enterprise Services
- [MUST] External input (federation/remote) is a trust boundary.
  - Apply SSRF/XSS/header-injection protections per downstream rules.
  - Federation details: `src/agent_server/services/federation/AGENTS.md`
- [SHOULD] Long-lived background tasks (cleanup/cron/outbox/partition bootstrap) must be started/stopped as a pair in lifespan.
  - Source of truth: `src/agent_server/main.py#lifespan`

---

## What’s Here (Service Map)

### Execution / Streaming
- `langgraph_service.py`: graph loading/caching/default assistant creation/A2A registration
- `streaming_service.py`: SSE orchestration (put/replay/flush)
- `event_store.py`: persistent `run_events`, replay, cleanup
- `broker.py`: per-run in-memory event queues (with backpressure)
- `event_converter.py`: LangGraph events → SSE events
- `thread_state_service.py`: LangGraph snapshot/state → API response conversion

### Assistants / Registry
- `assistant_service.py`: assistant CRUD/versioning/graph schema
- `agent_registry_service.py`: local (A2A) agent registry

### Org / RBAC / Rate Limit / Audit / Cron
- `organization_service.py`, `rbac_service.py`, `permission_service.py`
- `quota_service.py`, `rate_limit_rule_service.py`, `rate_limit_analytics_service.py`
- `audit_outbox_service.py`, `partition_service.py`
- `cron_scheduler_service.py`, `thread_cleanup_service.py`
- `feature_flag_service.py`, `cache_service.py`

### Submodules
- Agent Auth: `src/agent_server/services/agent_auth/AGENTS.md`
- Federation: `src/agent_server/services/federation/AGENTS.md`

---

## Common Tasks

### 1) Add a new service
1. Create `src/agent_server/services/<name>_service.py` (prefer `TracedService` where appropriate)
2. Provide `get_<name>_service()` for DI if needed
3. Call it from the API layer (`src/agent_server/api/*`)
4. Add tests at the right level (unit → integration → e2e)

### 2) Debug streaming / reconnect issues
- Priority order: `streaming_service.py` → `event_store.py` → `broker.py` → `api/runs.py`

### 3) Debug federation / remote issues
- Validate SSRF/XSS protections first: `src/agent_server/utils/url_validator.py`, `src/agent_server/utils/sanitize.py`
- Network timeouts/retries/circuit breakers: `src/agent_server/core/resilience.py`

---

## References
- Upstream (server-wide rules): `src/agent_server/AGENTS.md`
- Core (sessions/DB/auth): `src/agent_server/core/AGENTS.md`
- API (HTTP contracts): `src/agent_server/api/AGENTS.md`
- Observability: `src/agent_server/observability/AGENTS.md`
- (Reference) Legacy long-form doc: `docs/agents_reference/services-layer.md`

## Keywords Router
- `open_langgraph.json`, `graph cache`, `compile` → `src/agent_server/services/langgraph_service.py`
- `SSE`, `replay`, `Last-Event-ID`, `flush` → `src/agent_server/services/streaming_service.py`, `src/agent_server/services/event_store.py`
- `BROKER_*`, `backpressure` → `src/agent_server/services/broker.py`
- `org`, `RBAC`, `quota`, `rate limit`, `audit` → `src/agent_server/services/organization_service.py` (and related services)
- `federation`, `remote`, `SSRF` → `src/agent_server/services/federation/AGENTS.md`
