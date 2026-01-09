# AGENTS.md - `tests/` (Test Suite MUST-KNOW)

This document keeps only MUST-KNOW guidance for the test tree.
Detailed guides/examples live in `tests/README.md` and the reference archive: `docs/agents_reference/tests-layer.md`.

## Purpose
- Provide invariants for writing/running tests quickly, safely, and reproducibly.

## Non-Goals
- Do not keep long-form tutorials, full directory maps, or large examples here.

---

## MUST-KNOW (Invariants)
- [MUST] If you add a new pytest marker, you must also add it to `pytest.ini` under `markers =` (`--strict-markers`).
- [MUST] Use markers that match test intent: `unit`, `integration`, `e2e`, `slow`, `db`, `sqlite`, `hitl`, `real_graph`.
- [MUST] E2E tests target a real running server.
  - Base URL: `SERVER_URL` (default `http://localhost:8000`)
  - Utility: `tests/e2e/_utils.py#get_e2e_client`
- [SHOULD] API/service tests should follow the fixture-based dependency override pattern.
  - App factory: `tests/fixtures/clients.py#create_test_app`
  - Client: `tests/fixtures/clients.py#make_client`
- [SHOULD] Async tests should follow repo configuration (`pytest.ini: asyncio_mode=auto`).
  - Use `@pytest.mark.asyncio` when matching existing patterns.

---

## Common Tasks
- All tests: `uv run pytest`
- Unit only: `uv run pytest tests/unit/`
- Integration only: `uv run pytest tests/integration/`
- Run E2E (server required):
  - 1) `docker compose up open-langgraph`
  - 2) `uv run pytest -m e2e`
  - (remote/other port) `SERVER_URL=http://localhost:8000 uv run pytest -m e2e`

---

## References
- Detailed guide: `tests/README.md`
- (Reference) Legacy long-form doc: `docs/agents_reference/tests-layer.md`
- Streaming tests: `tests/e2e/test_streaming/`
- Streaming implementation: `src/agent_server/services/streaming_service.py`, `src/agent_server/api/runs.py`

## Keywords Router
- `SERVER_URL`, `get_e2e_client` → `tests/e2e/_utils.py`
- `markers`, `--strict-markers` → `pytest.ini`
- `create_test_app`, `make_client` → `tests/fixtures/clients.py`
