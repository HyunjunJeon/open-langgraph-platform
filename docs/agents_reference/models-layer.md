# (Reference) Models Layer (`src/agent_server/models/`)

> This is a long-form reference companion to `src/agent_server/models/AGENTS.md`.
> Prefer the MUST-KNOW guide in `src/agent_server/models/AGENTS.md` when making changes.

## What this layer does

`src/agent_server/models/` defines the Pydantic schemas that form the server’s public and internal
contracts:

- request/response bodies for Agent Protocol endpoints (FastAPI `response_model=...`)
- shared value objects used across API/services (e.g., pagination, filters)
- standardized error shapes

## Invariants (high-signal)

- Keep **Agent Protocol / SDK compatibility**.
  - Avoid renaming fields or changing field types.
  - Prefer **additive** changes (new optional fields) over breaking changes.
- Do not leak sensitive information.
  - Avoid returning secrets in responses.
  - Be careful with debug/error payloads and audit exports.
- Keep models deterministic and JSON-serializable.
  - Anything persisted or streamed must have stable serialization.

## Where models are used

- API layer: route handlers validate inputs and shape outputs with these models.
- Services layer: constructs domain objects and returns data that matches API models.
- Middleware/observability/audit: uses specialized models for logs/events where needed.

## High-signal modules (examples)

Core Agent Protocol resources:

- `assistants.py`
- `threads.py`
- `runs.py`
- `store.py`
- `errors.py`

Operational / multi-tenant / enterprise areas:

- `organization.py`, `rbac.py`, `auth.py`
- `audit.py`
- `rate_limit.py`, `rate_limit_rules.py`
- `feature_flags.py`
- `crons.py`

## Common tasks

### Add a new endpoint

1. Add request/response models (prefer explicit schemas).
2. Wire them into the router (`src/agent_server/api/...`) using `response_model=...`.
3. Update tests to lock in the contract.

### Change an existing model

1. Verify compatibility with existing clients (SDK expectations).
2. Prefer making fields optional instead of removing/retyping fields.
3. Update any integration tests that assert response shapes.

## Related docs

- `src/agent_server/models/AGENTS.md`
- `src/agent_server/api/AGENTS.md`

