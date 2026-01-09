# Contributing Guide

This project is a FastAPI-based Agent Protocol server aiming to provide a self-hosted alternative to the LangGraph Platform.
Before contributing, please read these docs first:

- Dev environment / workflow: `docs/developer-guide.md`
- Code quality / hooks / commit rules: `docs/code-quality.md`
- DB migrations: `docs/migration-cheatsheet.md`, `alembic/AGENTS.md`
- AGENTS hierarchy (long-term memory): `AGENTS.md`, `agents_hierarchy_design.md`

Note: Some detailed guides are still maintained in Korean; the English files are currently lightweight pointers.

---

## Quick start (dev environment)

```bash
uv sync --all-extras
cp .env.example .env
docker compose up open-langgraph
```

Run locally (without Docker):

```bash
uv run python run_server.py
```

---

## Validate changes

```bash
uv run pytest
make format
make lint
make type-check
```

Recommended (run the full CI suite locally):

```bash
make ci-check
```

---

## PR principles (Upstream / Downstream)

- Prefer fixing the root cause for features/bug fixes.
- Do not break the API contract (Agent Protocol) or the LangGraph execution/state persistence contract.
- Always verify multi-tenant scoping (`identity`, `org_id`); missing scope can lead to data leaks.
- When changing docs/AGENTS, do not link to paths/commands that don’t exist.

---

## Issues / questions

- Bugs / feature requests: GitHub Issues
- Design / discussion: GitHub Discussions
