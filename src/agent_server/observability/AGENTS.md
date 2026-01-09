# AGENTS.md - `src/agent_server/observability/` (Tracing & Observability)

This document keeps only MUST-KNOW guidance for the observability module.
Long-form details are delegated to: `docs/agents_reference/observability.md`.

## Purpose
- Trace service and graph execution using OpenTelemetry (standard) and Langfuse (LLM tracing).
- Provide auto-tracing for service methods to ensure baseline visibility.

## Non-Goals
- Do not implement business logic here (observe behavior; services own behavior).

---

## MUST-KNOW (Invariants)
- [MUST] Observability is optional; when disabled, runtime overhead must be minimal/near-zero.
  - Primary gate: `OTEL_ENABLED=false`
- [MUST] Service auto-tracing is applied via `TracedService` inheritance or the `@traced_service` decorator.
  - Implementation: `src/agent_server/observability/auto_tracing.py`
- [SHOULD] Use manual tracing decorators for targeted spans when needed.
  - Implementation: `src/agent_server/observability/tracing.py`
- [REF] Langfuse callbacks are injected into LangGraph execution config.
  - Implementation: `src/agent_server/observability/langfuse_integration.py`

---

## Common Tasks

### Enable OpenTelemetry
- Set `OTEL_ENABLED=true` and exporter config in `.env`.
- OTEL dependencies may require extras (`open-langgraph-platform[otel]`).

### Enable service method auto-tracing
- Prefer `TracedService` for new service classes.
- Parameter names (assistant_id/thread_id/run_id, etc.) are used for attribute extraction.

---

## References
- Server lifespan (OTEL setup/shutdown): `src/agent_server/main.py`
- Langfuse setup guide: `docs/langfuse-usage.md`
- (Reference) Legacy long-form doc: `docs/agents_reference/observability.md`

## Keywords Router
- `OTEL_ENABLED`, `setup_opentelemetry` → `src/agent_server/observability/otel_integration.py`
- `TracedService`, `traced_service` → `src/agent_server/observability/auto_tracing.py`
- `Langfuse`, `callbacks` → `src/agent_server/observability/langfuse_integration.py`
