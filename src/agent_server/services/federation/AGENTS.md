# AGENTS.md - `src/agent_server/services/federation/` (Federation & Remote Agents)

This directory discovers A2A agents from external peers (remote servers) and provides context/security utilities for remote calls.

## Purpose
- Collect `/a2a/` listings from federation peers and resolve AgentCards.
- Standardize retries/circuit breakers/timeouts/header propagation for remote calls.
- Treat peer responses as untrusted input and apply SSRF/XSS/header-injection defenses.

## Non-Goals
- Local graph registration/compilation/execution is owned by `langgraph_service.py`.
- A2A protocol routing/execution is owned by `src/agent_server/a2a/`.

---

## MUST-KNOW (Security Invariants)
- [MUST] Peer-provided URLs must pass SSRF validation.
  - Single source of truth: `validate_url_for_ssrf()`
  - File: `src/agent_server/utils/url_validator.py`
- [MUST] Peer-provided text (name/description/tags) must be sanitized (defense-in-depth for XSS).
  - File: `src/agent_server/utils/sanitize.py`
- [MUST] Header propagation must include header-injection defenses (CR/LF stripping).
  - Implementation: `RemoteA2AClient._sanitize_header_value()`
- [SHOULD] Mitigate network instability with retries/circuit breakers.
  - Implementation: `src/agent_server/core/resilience.py` (used by federation)

---

## Config Surface

Federation settings are read from the `federation` section of `open_langgraph.json` (LangGraphService config).
- Parser: `src/agent_server/services/federation/config.py#parse_federation_config`
- Key fields: `peers[]` → `id`, `base_url`, `auth_type`, `auth_token`, `timeout_ms`

---

## Operational Notes
- `FederationService` caches an `httpx.AsyncClient` per peer.
  - Ensure clients are closed on shutdown to avoid connection leaks in long-lived processes.

---

## References
- FederationService: `src/agent_server/services/federation/federation_service.py`
- Remote client: `src/agent_server/services/federation/remote_a2a_client.py`
- Context propagation (W3C trace context): `src/agent_server/services/federation/context_propagation.py`
- API entrypoint (remote agent listing): `src/agent_server/api/agents.py`
