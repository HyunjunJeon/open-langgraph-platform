# (Reference) Services Layer (`src/agent_server/services/`)

> This is a long-form reference companion to `src/agent_server/services/AGENTS.md`.
> Prefer the MUST-KNOW guide in `src/agent_server/services/AGENTS.md`.

## What this layer does

Services own the server’s business logic and orchestration:

- LangGraph graph loading + execution orchestration
- assistants/threads/runs workflows on top of persisted metadata
- streaming orchestration (SSE) and event replay
- operational services (audit outbox, partitions, quotas/RBAC, feature flags, cron scheduling)
- optional integrations (cache, federation, agent auth)

API handlers should delegate to services and avoid embedding complex logic in routers.

## High-signal services (examples)

Graph & execution:

- `langgraph_service.py`: loads graphs from `open_langgraph.json`, compiles with persistence, caches
- `assistant_service.py`: assistant CRUD + versioning semantics
- `thread_state_service.py`: thread state/history operations

Streaming:

- `streaming_service.py`: orchestrates streaming, reconnect, and replay
- `event_store.py`: persists events for replay (tenant-scoped)
- `broker.py`: fan-out to active subscribers
- `event_converter.py`: normalizes/serializes LangGraph events for API/SSE

Operations:

- `audit_outbox_service.py`: crash-safe audit outbox insertion + background mover
- `partition_service.py`: manages partitioned tables/retention where used
- `quota_service.py`, `rbac_service.py`: org quotas and permissions
- `rate_limit_rule_service.py`, `rate_limit_analytics_service.py`: rate limiting rule mgmt/analytics
- `cron_scheduler_service.py`: scheduling/cron orchestration (when enabled)

## Streaming architecture (conceptual)

```
LangGraph execution
  -> convert events (service)
  -> persist events (event_store)
  -> publish events (broker)
  -> API streams via SSE
  -> reconnect uses stored events + Last-Event-ID
```

## Invariants

- Tenant scoping (`identity`, `org_id`) must be enforced in all data access.
- Services should not duplicate Core infrastructure logic (DB sessions, SSE formatting).
- Optional infra should degrade gracefully when disabled (cache/redis/otel/etc.).

## References

- `src/agent_server/services/AGENTS.md`
- `src/agent_server/core/AGENTS.md`
- `src/agent_server/api/AGENTS.md`

