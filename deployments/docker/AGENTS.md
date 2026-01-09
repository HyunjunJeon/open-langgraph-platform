# AGENTS.md - `deployments/docker/` (Dockerfile)

This directory contains the Dockerfile used to build container images.

## Purpose
- Provide the source of truth for image build and runtime packaging.

## Non-Goals
- Runtime execution policy (migrations/uvicorn) is owned by `docker-compose.yml`.

---

## MUST-KNOW (Invariants)
- [MUST] Dockerfile: `deployments/docker/Dockerfile`
- [SHOULD] Run the container as a non-root user (`app`).
- [MUST] Include required runtime assets (`alembic.ini`, `alembic/`, `open_langgraph.json`, `auth.py`, `graphs/`, `src/`).

---

## References
- Compose entrypoint (migrations + uvicorn): `docker-compose.yml`
- Server entrypoint: `src/agent_server/main.py`
