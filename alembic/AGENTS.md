# AGENTS.md - `alembic/` (Migrations MUST-KNOW)

This document keeps only MUST-KNOW guidance for migrations.
Long-form details are delegated to: `docs/agents_reference/alembic-layer.md`.

## Purpose
- Version database schema for Agent Protocol metadata (ORM-driven) using Alembic.

## Non-Goals
- Do not maintain long-form schema timelines or deep troubleshooting here (delegate to docs/reference).

---

## MUST-KNOW (Invariants)
- [MUST] Migration source of truth: `alembic/versions/` + `alembic/env.py`
  - `alembic/env.py` uses `Base.metadata` from `src/agent_server/core/orm.py`.
- [MUST] DB URL precedence: `DATABASE_URL` env var → `alembic.ini` `sqlalchemy.url`
  - Explicitly set `DATABASE_URL` in local/CI/docker environments.
- [MUST] Filename conventions follow `alembic.ini` `file_template` (timestamp-based).
- [MUST] For schema changes:
  - 1) update `src/agent_server/core/orm.py`
  - 2) generate a migration (autogenerate)
  - 3) apply/verify (tests or local run)
- [SHOULD] Implement downgrades when possible (dev rollback/reset).
- [REF] Docker Compose runs `alembic upgrade head` on startup (`docker-compose.yml`).

---

## Common Tasks
- Apply latest: `uv run alembic upgrade head`
- Create a new migration: `uv run alembic revision --autogenerate -m "add_feature"`
- Show current version: `uv run alembic current`
- Show history: `uv run alembic history --verbose`
- Roll back one step: `uv run alembic downgrade -1`
- Reset (dangerous): `uv run alembic downgrade base && uv run alembic upgrade head`

---

## References
- Migration cheat sheet: `docs/migration-cheatsheet.md`, `docs/migration-cheatsheet-ko.md`
- Developer guide: `docs/developer-guide.md`, `docs/developer-guide-ko.md`
- ORM models: `src/agent_server/core/orm.py`
- (Reference) Legacy long-form doc: `docs/agents_reference/alembic-layer.md`

## Keywords Router
- `DATABASE_URL`, `env.py` → `alembic/env.py`, `alembic.ini`
- `revision`, `autogenerate` → `uv run alembic revision ...`, `src/agent_server/core/orm.py`
