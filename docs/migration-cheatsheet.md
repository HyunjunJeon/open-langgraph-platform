# Migration Cheatsheet (English)

The canonical migration cheatsheet is currently maintained in Korean:
[migration-cheatsheet-ko.md](migration-cheatsheet-ko.md).

This file is a short pointer so internal links stay valid.

## Quick Commands
- Apply all pending migrations: `uv run alembic upgrade head`
- Create a new migration: `uv run alembic revision --autogenerate -m "Description"`
- Rollback last migration: `uv run alembic downgrade -1`
- Check current revision: `uv run alembic current`
- View history: `uv run alembic history --verbose`
- Reset schema (DANGEROUS): `uv run alembic downgrade base && uv run alembic upgrade head`
