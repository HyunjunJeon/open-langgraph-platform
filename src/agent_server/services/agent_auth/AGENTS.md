# AGENTS.md - `src/agent_server/services/agent_auth/` (Agent Identity & Credentials)

This directory is not user authentication (`auth.py`). It manages remote agent (Agent-to-Agent) identities and credentials.

## Purpose
- Register agent identities per organization and issue/revoke credentials.
- Provide the authentication substrate used by A2A/federation when calling external agents.

## Non-Goals
- Human (user) authn/authz policies are owned by `auth.py` and `src/agent_server/core/auth_*`.
- A2A protocol translation/execution is owned by `src/agent_server/a2a/`.

---

## MUST-KNOW (Invariants)
- [MUST] All operations are protected by org membership/RBAC.
  - Minimum role requirements are checked using `OrganizationRole`.
  - Implementation: `src/agent_server/services/agent_auth/service.py`
- [MUST] Credential fingerprints are treated as globally unique; duplicates are blocked with 409.
  - Implementation: `AgentAuthService.create_credential()` (pre-check via DB query)
- [MUST] JWT verification must explicitly enforce key/alg/issuer/audience/exp(require).
  - Implementation: `src/agent_server/services/agent_auth/jwt_verifier.py`
- [SHOULD] Normalize JWT claims across common schemas (`scope`, `scp`, `scopes`, `org_id`/`org`, `agent_id`/`sub`).

---

## API Surface (Where Used)
- Router: `src/agent_server/api/agent_auth.py`
  - Prefix: `/organizations/{org_id}/agents`
- Metadata/storage: `src/agent_server/core/orm.py`
  - Tables: `AgentIdentity`, `AgentCredential`

---

## Common Tasks

### Add a new credential type
1. Extend `AgentCredentialType` in `models.py`
2. Add creation/validation logic in `service.py`
3. If needed, update DB schema/indexes → create an Alembic migration
4. Update API models/routers/tests

---

## References
- Org/RBAC services: `src/agent_server/services/organization_service.py`, `src/agent_server/services/rbac_service.py`
- A2A layer: `src/agent_server/a2a/AGENTS.md`
