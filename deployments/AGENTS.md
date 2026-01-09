# AGENTS.md - `deployments/` (Deployment Artifacts)

This document covers deployment/container artifacts under `deployments/`.
Application logic is owned by `src/agent_server/`; this document focuses on operations (build/run/env).

## Purpose
- Make Docker-based local/production deployment entry points easy to find.
- Fix the source-of-truth paths for Dockerfiles and compose files.

## Non-Goals
- Do not document application code structure or business logic here (delegate to server-layer docs).

---

## MUST-KNOW (Invariants)
- [MUST] Dockerfile path: `deployments/docker/Dockerfile`
- [MUST] Local compose path: `docker-compose.yml`
- [MUST] Containers are configured to run `alembic upgrade head` on startup (see `docker-compose.yml` `command`).
- [SHOULD] Do not bake secrets (API keys, etc.) into images; inject via `.env` / secret managers.

---

## Common Tasks

### Local development (Docker Compose)
- Run: `docker compose up open-langgraph`
- DB runs as the compose `postgres` service; `DATABASE_URL` uses the container hostname.

### Build a Docker image
- Without compose:
  - `docker build -f deployments/docker/Dockerfile -t open-langgraph .`

---

## References
- Server entrypoint: `src/agent_server/main.py`
- Env template: `.env.example`
- DB migrations: `alembic/AGENTS.md`
