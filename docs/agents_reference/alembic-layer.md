# (Reference) Alembic Layer (Database Migrations)

> This is a long-form reference companion to `alembic/AGENTS.md`.
> Prefer `alembic/AGENTS.md` for MUST-KNOW rules and project-specific constraints.

## What this layer does

The `alembic/` directory manages schema versioning for the Postgres metadata tables used by the
Agent Protocol server. It is intentionally focused on **metadata persistence** (ORM tables),
while **LangGraph state** is persisted via the LangGraph checkpointer/store (not via extra ORM
tables unless required for metadata).

## Key files

- `alembic/env.py`: Alembic environment setup (async engine/session integration).
- `alembic/versions/`: Migration scripts (one file per revision).
- `alembic.ini`: Base configuration (URL is typically provided via env vars).

## Common workflows

### Apply all pending migrations

```bash
uv run alembic upgrade head
```

### Create a new migration

Autogenerate from ORM changes:

```bash
uv run alembic revision --autogenerate -m "add_<thing>"
```

Create an empty migration (manual SQL/ops):

```bash
uv run alembic revision -m "manual_<thing>"
```

### Roll back

```bash
uv run alembic downgrade -1
```

## Safety / best practices

- Prefer additive, backward-compatible changes first (new nullable columns, new tables).
- For large tables, avoid long locks:
  - create indexes concurrently (manual migration)
  - backfill in a separate step/job when possible
- Always validate both directions locally:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
```

## Troubleshooting

### "Target database is not up to date"

```bash
uv run alembic current
uv run alembic upgrade head
```

### "Can't locate revision"

- A revision file is missing or the DB points at a revision you no longer have.

```bash
uv run alembic history --verbose
```

### "Multiple head revisions"

```bash
uv run alembic heads
uv run alembic merge -m "merge_heads" <rev1> <rev2>
```

## Related docs

- `docs/migration-cheatsheet.md`
- `alembic/AGENTS.md`

