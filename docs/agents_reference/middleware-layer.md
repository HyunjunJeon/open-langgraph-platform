# (Reference) Middleware Layer (Request Cross-Cutting Concerns)

> This is a long-form reference companion to `src/agent_server/middleware/AGENTS.md`.
> Prefer the MUST-KNOW guide in `src/agent_server/middleware/AGENTS.md` for day-to-day work.

## Why middleware matters here

In Open LangGraph, middleware is where most cross-cutting guarantees are enforced:

- auditability
- rate limiting / abuse protection
- authentication context propagation
- payload normalization for quirky clients

Because these concerns are security-sensitive, middleware ordering and tenant scoping must be
treated as part of the server’s API contract.

## Ordering (source of truth)

Middleware order is defined by `src/agent_server/main.py` and must not be changed casually.
The intended ordering is:

1. Audit
2. Rate limiting
3. Authentication
4. Double-encoded JSON normalization
5. CORS
6. Router

If the code and docs disagree, **the code wins**—update the docs after verifying behavior.

## Key modules

- `src/agent_server/middleware/audit.py`
  - Captures request metadata (identity + org scoping).
  - Applies masking before persistence/export to avoid leaking secrets.
- `src/agent_server/middleware/rate_limit.py`
  - Enforces request budgets (global + endpoint buckets).
  - Should be fail-open or fail-closed based on explicit configuration.
- `src/agent_server/middleware/double_encoded_json.py`
  - Normalizes `\"{...}\"` payload patterns sometimes produced by SDKs/proxies.

## Common pitfalls

- **Tenant leaks**: always ensure `identity` and `org_id` are present where required.
- **Trusting user-controlled headers**: never trust inbound headers for identity/tenancy.
- **Streaming edge cases**: SSE endpoints may end with client disconnects; make sure audit
  semantics handle `499` correctly if you rely on that status.

## Related docs

- `docs/audit-logging.md`
- `docs/rate-limiting.md`
- `src/agent_server/middleware/AGENTS.md`
- `src/agent_server/AGENTS.md`

