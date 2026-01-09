# Developer Guide (English)

The canonical developer guide is currently maintained in Korean:
[developer-guide-ko.md](developer-guide-ko.md).

This file is a short pointer so internal links stay valid.

## Quick Commands
- Install deps: `uv sync --all-extras`
- Start (Docker): `docker compose up open-langgraph`
- Migrations: `uv run alembic upgrade head` (or `alembic upgrade head`)
- Tests: `uv run pytest`
- Format/Lint/Type-check: `make format`, `make lint`, `make type-check`
