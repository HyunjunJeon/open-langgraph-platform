# AGENTS.md - `src/agent_server/utils/` (Shared Utilities)

This directory contains shared utilities used across layers (API/Services/Core/Middleware).

## Purpose
- Centralize small, reusable logic to reduce duplication.
- Keep security/correctness utilities (masking/SSRF defense/normalization) as single sources of truth.

## Non-Goals
- Do not pull in business logic (policy decisions/DB transactions/permission checks).
- Do not implement request handling or LangGraph execution orchestration here.

---

## Scope & Boundaries

### In scope (this directory owns)
- Pure functions and lightweight helpers (strings/IDs/paths/event IDs)
- Security utilities (masking secrets, sanitizing text, SSRF-safe URL validation)

### Dependency rules (important)
- [MUST] `utils/` must not depend on higher layers (`api/`, `services/`).
- [SHOULD] Keep dependencies on `core/` minimal to avoid cycles.
- [SHOULD] If types are needed, depend on contracts such as Pydantic/Enums in `models/`.

---

## MUST-KNOW (Invariants)
- [MUST] SSE event ID format is `{run_id}_event_{seq}`; `generate_event_id()` / `extract_event_sequence()` are the single source of truth.
  - File: `src/agent_server/utils/sse_utils.py`
- [MUST] Mask sensitive data before persisting audit logs.
  - File: `src/agent_server/utils/masking.py`
- [MUST] Treat federation/remote input as untrusted:
  - Text sanitization: `src/agent_server/utils/sanitize.py`
  - URL SSRF validation: `src/agent_server/utils/url_validator.py`
- [SHOULD] The "graph_id → assistant_id" derivation rules are owned by `resolve_assistant_id()`.
  - File: `src/agent_server/utils/assistants.py`

---

## What’s Here (Map)
- `assistants.py`: derive a deterministic assistant_id from graph_id (`uuid5` + namespace)
- `sse_utils.py`: generate/parse SSE event IDs
- `audit_helpers.py`: infer audit action/resource from HTTP method/path; extract resource_id
- `masking.py`: audit log masking (with recursion/depth/length limits)
- `sanitize.py`: defense-in-depth sanitization/escaping for external text
- `url_validator.py`: SSRF-safe URL validation for federation/remote calls
- `cron.py`: validate cron expressions and compute next run time (croniter)

---

## Common Tasks

### Checklist for adding a new utility
- [MUST] Can it run without I/O (network/DB/files)? If not, move it to `services/`.
- [MUST] If it accepts external input, consider size limits/normalization/exception messaging (log injection defense).
- [SHOULD] Verify import direction does not introduce cycles.

---

## References
- Audit middleware (uses masking/inference): `src/agent_server/middleware/audit.py`
- Federation (uses SSRF/sanitize): `src/agent_server/services/federation/federation_service.py`
