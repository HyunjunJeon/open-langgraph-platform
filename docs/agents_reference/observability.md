# (Reference) Observability Layer (Tracing & Monitoring)

> This is a long-form reference companion to `src/agent_server/observability/AGENTS.md`.
> Prefer `src/agent_server/observability/AGENTS.md` for MUST-KNOW rules.

## Goals

- Provide optional, low-overhead tracing that can be enabled in production.
- Make it possible to trace:
  - HTTP requests
  - service methods (business logic)
  - LangGraph execution (where instrumented)
- Support OpenTelemetry as the “standard path”.
- Provide Langfuse integration as an optional LLM-focused tracing destination.

## Key modules

- `src/agent_server/observability/otel_integration.py`
  - Initializes OpenTelemetry SDK, exporters, and instrumentations.
- `src/agent_server/observability/auto_tracing.py`
  - Utilities to auto-wrap service methods (opt-in).
- `src/agent_server/observability/tracing.py`
  - Explicit decorators/utilities for fine-grained spans.
- `src/agent_server/observability/langfuse_integration.py`
  - Provides Langfuse callbacks/hooks where applicable.

## Wiring / lifecycle

Observability is typically initialized during app startup (`lifespan`) in `src/agent_server/main.py`.
Treat initialization as best-effort: observability should not prevent the server from starting
unless the deployment explicitly requires it.

## Operational guidance

- Avoid logging secrets: combine request masking + structured span attributes.
- Prefer bounded cardinality for span attributes (IDs OK, raw payloads not OK).
- When debugging “missing traces”:
  - confirm exporter env vars
  - confirm instrumentation is enabled
  - confirm background tasks are not swallowed silently

## Related docs

- `docs/langfuse-usage.md`
- `src/agent_server/observability/AGENTS.md`

