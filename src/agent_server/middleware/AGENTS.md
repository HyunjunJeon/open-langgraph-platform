# AGENTS.md - `src/agent_server/middleware/` (Cross-Cutting Concerns)

This document keeps only MUST-KNOW guidance for `src/agent_server/middleware/`.
Long-form details are delegated to: `docs/agents_reference/middleware-layer.md`.

## Purpose
- Handle cross-cutting HTTP concerns applied to all requests (audit logging, rate limiting, input normalization).

## Non-Goals
- Authentication logic itself is owned by Core (`src/agent_server/core/auth_*`).
- Business logic is owned by Services.

---

## MUST-KNOW (Invariants)
- [MUST] Middleware execution order is defined by registration order in `src/agent_server/main.py` (reverse execution).
  - Request path: Audit → RateLimit → Authentication → DoubleEncodedJSON → CORS → Router
- [MUST] Audit logging is a security/compliance feature; keep "excluded paths" minimal.
  - Implementation: `src/agent_server/middleware/audit.py`
- [MUST] Mask sensitive data before persisting audit logs.
  - Implementation: `src/agent_server/utils/masking.py`
- [SHOULD] Rate limiting is optional (graceful degradation when Redis/slowapi is missing); production policy is env-driven.
  - Core implementation: `src/agent_server/core/rate_limiter.py`
- [SHOULD] Double-encoded JSON handling exists for client compatibility; if parsing fails, preserve the original payload.

---

## What’s Here (Map)
- `audit.py`: Outbox-based audit logging (also wraps streaming responses)
- `rate_limit.py`: request limiting middleware (org/user/IP keys)
- `double_encoded_json.py`: normalize double-encoded JSON

---

## Common Tasks

### Audit logging changes
- If you must add an excluded path:
  - Verify it is truly static/harmless/high-frequency.
  - Prefer exact matches; broad prefix exclusions create large blind spots.

### Rate limit policy changes
- Review env vars (e.g., `RATE_LIMIT_*`) alongside the Core implementation.
- Production must explicitly set fail-open/closed (`RATE_LIMIT_FALLBACK`).

---

## References
- Server-wide rules: `src/agent_server/AGENTS.md`
- Core rate limiter: `src/agent_server/core/rate_limiter.py`
- Audit outbox mover: `src/agent_server/services/audit_outbox_service.py`
- (Reference) Legacy long-form doc: `docs/agents_reference/middleware-layer.md`

## Keywords Router
- `audit`, `outbox`, `masking` → `src/agent_server/middleware/audit.py`, `src/agent_server/utils/masking.py`
- `rate limit`, `slowapi`, `redis` → `src/agent_server/core/rate_limiter.py`
- `double encoded json` → `src/agent_server/middleware/double_encoded_json.py`
